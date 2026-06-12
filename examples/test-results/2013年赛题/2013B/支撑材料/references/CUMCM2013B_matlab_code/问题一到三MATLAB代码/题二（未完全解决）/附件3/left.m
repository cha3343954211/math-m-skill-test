function [tou] = left(cell)

tou = [];
for i = 1:length(cell)
    if cell{1,i}(:,1:6) == 255
        tou = [tou,i];
    end
end


end

